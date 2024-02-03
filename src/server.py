import json
import logging
import os
import random
import signal
import string
import sys
from pathlib import Path
from typing import Dict, List

from apiflask import APIFlask, Schema, FileSchema
import apiflask.fields as fields
import apiflask.validators as validators
from flask import render_template, url_for, request, Response
from flask_cors import CORS
from pytesseract import pytesseract
from werkzeug.datastructures import FileStorage

from helpers.prepare_files import prepare_files, optimize_image
from helpers.process_data import process_data

# todo: https://stackoverflow.com/a/16993115/2073149
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger('PIL').setLevel(logging.INFO)

app = APIFlask(
    __name__,
    title='ABC-Soup',
    version='0.0.5',
)
CORS(app)


def on_signal(signal_number, frame):
    logging.info(f'shutting down {signal_number}')
    # s.shutdown()


# signal.signal(signal.SIGKILL, on_signal)
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)


@app.route('/')
def route_home():
    links = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        url = url_for(rule.endpoint, **(rule.defaults or {}))
        methods = rule.methods.copy()
        if 'HEAD' in methods:
            methods.remove('HEAD')
        if 'OPTIONS' in methods:
            methods.remove('OPTIONS')
        links.append((url, list(methods), rule.endpoint, rule.arguments, rule.defaults))
    return render_template('index.html', version=os.environ.get('APP_ENV', 'dev'), links=links)


class ServerInfo(Schema):
    languages = fields.List(
        fields.String(),
        example=['eng']
    )
    tesseract_version = fields.String(example=str(pytesseract.get_tesseract_version()))


@app.route('/info')
@app.output(ServerInfo)
@app.doc(operation_id='info', summary='Get OCR-Engine Info')
def route_info():
    return {
        "languages": pytesseract.get_languages(),
        "tesseract_version": str(pytesseract.get_tesseract_version()),
    }


def build_config(options: Dict):
    psm = options.get('psm', None)  # https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method
    preserve_interword_spaces = options.get('preserve_interword_spaces', None)  # preserve_interword_spaces=1

    config = []
    if psm is not None:
        config.append(fr'--psm {psm}')
    if preserve_interword_spaces is not None:
        config.append(fr'-c preserve_interword_spaces={preserve_interword_spaces}')

    return config


def parse_options(form_options):
    options = json.loads(form_options) if form_options else default_options
    if 'lang' in options and isinstance(options['lang'], list):
        options['lang'] = '+'.join(options['lang'])

    return {
        **default_options,
        **options,
    }


default_options_pdf = {
    'lang': os.environ.get('DEFAULT_LANG', 'eng+deu'),
    'optimize_images': True,
    'save_intermediate': False,
}

default_options = {
    **default_options_pdf,
    'optimize_images': False,
    'intra_block_breaks': True,
    'keep_details': False,
}


def process_request(files: List[FileStorage], options: Dict):
    lang = options['lang']
    optimize_images = options['optimize_images']
    save_intermediate = options['save_intermediate']
    intra_block_breaks = options['intra_block_breaks']
    keep_details = options['keep_details']
    config = build_config(options)

    image_paths, infer_file, infer_id = prepare_files(files, optimize=optimize_images, save_intermediate=save_intermediate)

    text: str = pytesseract.image_to_data(
        infer_file, lang=lang,
        config=' '.join(config),
    )

    for image_path in image_paths:
        os.unlink(image_path)
    if infer_file not in image_paths:
        os.unlink(infer_file)

    return process_data(files, text, intra_block_breaks, keep_details)


class OCROptions(Schema):
    # todo: lang can be string or array, doesn't matter as long as the validation for `options` isn't activated in APIFlask
    lang = fields.String(required=True)
    optimize_images = fields.Boolean()
    save_intermediate = fields.Boolean()
    intra_block_breaks = fields.Boolean()
    keep_details = fields.Boolean()
    psm = fields.Integer(
        externalDocs='https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method'
    )
    preserve_interword_spaces = fields.Integer()


class OCRInput(Schema):
    file = fields.File(required=True, validate=[validators.FileType(['.png', '.jpg', '.jpeg'])])
    # todo: refactor to other field based strings for API-interface and internally mapping to clean flags
    options = fields.String(example=json.dumps(default_options))
    # options = OCROptions()


class Files(fields.Dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.metadata['type'] = 'object'
        self.metadata["patternProperties"] = {
            ".*": {"type": "string", "format": "binary"},
        }


class OCRInputBatch(Schema):
    # todo: APIFlask doesn't support patternProperties and seems to filter out them,
    #       as long as it can't validate dynamic length files, it can't be used for batch-input
    # files = fields.Dict(
    #     fields.String(),
    #     fields.File(required=True, validate=[validators.FileType(['.png', '.jpg', '.jpeg'])]),
    #     minProperties=1,
    #
    # todo: refactor to other field based strings for API-interface and internally mapping to clean flags
    options = fields.String(example=json.dumps(default_options))
    # options = OCROptions()


class OCRInputForPDF(Schema):
    file = fields.File(required=True, validate=[validators.FileType(['.png', '.jpg', '.jpeg'])])
    # todo: refactor to other field based strings for API-interface and internally mapping to clean flags
    options = fields.String(example=json.dumps(default_options_pdf))
    # options = OCROptions()


class ExtractedBox(Schema):
    level = fields.Integer()
    page_num = fields.Integer()
    block_num = fields.Integer()
    par_num = fields.Integer()
    line_num = fields.Integer()
    word_num = fields.Integer()
    left = fields.Integer()
    top = fields.Integer()
    width = fields.Integer()
    height = fields.Integer()
    conf = fields.Float()


class ExtractedBlock(Schema):
    block = fields.Integer(metadata={'description': 'The ID of the first box in this block'})
    boxes = fields.List(fields.Nested(ExtractedBox()), metadata={'description': 'All boxes with their respective position and text'})
    # text = fields.String(metadata={'description': """The text of all boxes in this block, using the positions to concatenate the texts of a box with the next one depending if below or right to the previous box, either with whitespaces or newlines.
    text = fields.String(metadata={'description': """The text of all boxes in this block, depending on the boxes positions either concatenated with whitespaces or newlines.

Disable adding newlines by setting `intra_block_breaks` to `false`."""})


class OCROutcome(Schema):
    """
    Result of OCR inference
    """
    page = fields.Integer(metadata={'description': 'Number of the page, only the *batch* endpoint returns multiple, each page is one input file.'})
    file = fields.String(metadata={'description': 'Name of the input file.'})
    content = fields.String(metadata={'description': 'Only if `keep_details` is `false`; The full content of the pages blocks as a combined string.'})
    blocks = fields.List(
        fields.Nested(ExtractedBlock()),
        metadata={'description': 'Only if `keep_details` is `true`; All blocks with their extracted boxes.'},
    )


class OCROutput(Schema):
    _usages = fields.List(fields.Dict())
    outcome = fields.Nested(OCROutcome())


class OCROutputBatch(Schema):
    _usages = fields.List(fields.Dict())
    outcome = fields.List(fields.Nested(OCROutcome()))


class ApiError(Schema):
    _usages = fields.List(fields.Dict())
    error = fields.String()


@app.post('/ocr')
@app.input(OCRInput, location='form_and_files')
@app.output(OCROutput)
# todo: get this working with multiple `.output` instead of the full response doc https://github.com/apiflask/apiflask/issues/327
@app.doc(operation_id='ocr', summary='Run OCR on a single file', responses={
    400: {
        'description': 'API Error',
        'content': {
            'application/json': {
                'schema': ApiError
            }
        }
    }
})
def route_ocr(form_and_files_data):
    file = form_and_files_data['file']
    if not file:
        return {'error': 'Missing "file"'}, 400

    options = parse_options(form_and_files_data['options'] if 'options' in form_and_files_data else None)
    pages = process_request([file], options)

    return {
        '_usages': [],
        # 'outcome': None if not pages else pages[0]['blocks'] if options['keep_details'] else pages[0]['content'],
        'outcome': None if not pages else pages[0],
    }


@app.post('/ocr-batch')
# @app.input(OCRInputBatch, location='form_and_files')
@app.output(OCROutputBatch)
# todo: get this working with multiple `.output` instead of the full response doc https://github.com/apiflask/apiflask/issues/327
@app.doc(operation_id='ocr_batch', summary='Run OCR on multiple files', responses={
    400: {
        'description': 'API Error',
        'content': {
            'application/json': {
                'schema': ApiError
            }
        }
    }
})
def route_ocr_batch():
    # files = form_and_files_data['files']
    # todo: support order-in-form and PDF
    files = list(request.files.values())
    if not files:
        return {'error': 'Missing files'}, 400

    options = parse_options(request.form['options'] if 'options' in request.form else None)
    # options = parse_options(form_and_files_data['options'] if 'options' in form_and_files_data else None)
    pages = process_request(files, options)

    return {
        '_usages': [],
        'outcome': pages,
    }


@app.post('/ocr-to-pdf')
@app.input(OCRInputForPDF, location='form_and_files')
@app.output(
    FileSchema(type='string', format='binary'),
    content_type='application/pdf',
    description='The generated PDF'
)
# todo: get this working with multiple `.output` instead of the full response doc https://github.com/apiflask/apiflask/issues/327
@app.doc(operation_id='ocr_pdf', summary='Generate PDF from single file', responses={
    400: {
        'description': 'API Error',
        'content': {
            'application/json': {
                'schema': ApiError
            }
        }
    }
})
def route_ocr_to_pdf(form_and_files_data):
    file = form_and_files_data['file']
    if not file:
        return {'error': 'Missing "file"'}, 400

    if 'intra_block_breaks' in request.form:
        return {'error': 'Option `intra_block_breaks` not supported'}, 400
    if 'keep_details' in request.form:
        return {'error': 'Option `keep_details` not supported'}, 400

    options = parse_options(form_and_files_data['options'] if 'options' in form_and_files_data else None)
    lang = options['lang']
    optimize_images = options['optimize_images']
    save_intermediate = options['save_intermediate']
    config = build_config(options)

    infer_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    pil_image = optimize_image(file, optimize_images, f'/app/shared-assets/pdf_{infer_id}_' if save_intermediate else None)

    binary_pdf = pytesseract.image_to_pdf_or_hocr(
        pil_image, lang=lang,
        config=' '.join(config),
        extension='pdf',
    )

    filename = Path(file.filename).stem
    response = Response(binary_pdf, content_type='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename="{filename}.pdf"'
    return response
