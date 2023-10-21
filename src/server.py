import json
import logging
import os
import random
import signal
import string
import sys
from pathlib import Path
from typing import Dict, List

from flask import Flask, render_template, url_for, request, make_response, Response
from flask_cors import CORS
from pytesseract import pytesseract
from werkzeug.datastructures import FileStorage

from helpers.prepare_files import prepare_files, optimize_image
from helpers.process_data import process_data

# todo: https://stackoverflow.com/a/16993115/2073149
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger('PIL').setLevel(logging.INFO)

app = Flask(__name__)
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


@app.route('/info')
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


def parse_options(form):
    options = json.loads(form['options']) if 'options' in form else default_options
    return {
        **default_options,
        **options,
    }


default_options = {
    'lang': 'eng+deu',
    'optimize_images': True,
    'save_intermediate': False,
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


@app.post('/ocr')
def route_ocr():
    file = request.files.get('file')
    if not file:
        return {'error': 'Missing "file"'}, 400

    options = parse_options(request.form)
    pages = process_request([file], options)

    return {
        '_usages': [],
        'outcome': None if not pages else pages[0]['blocks'] if options['keep_details'] else pages[0]['content'],
    }


@app.post('/ocr-batch')
def route_ocr_batch():
    files = list(request.files.values())
    if not files:
        return {'error': 'Missing files'}, 400

    options = parse_options(request.form)
    pages = process_request(files, options)

    return {
        '_usages': [],
        'outcome': pages,
    }


@app.post('/ocr-to-pdf')
def route_ocr_to_pdf():
    file = request.files.get('file')
    if not file:
        return {'error': 'Missing "file"'}, 400

    if 'intra_block_breaks' in request.form:
        return {'error': 'Option `intra_block_breaks` not supported'}, 400
    if 'keep_details' in request.form:
        return {'error': 'Option `keep_details` not supported'}, 400

    options = parse_options(request.form)
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
