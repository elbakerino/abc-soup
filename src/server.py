import json
import logging
import os
import signal
import sys
from typing import Dict

from flask import Flask, render_template, url_for, request
from flask_cors import CORS
from pytesseract import pytesseract

from helpers.prepare_files import prepare_files
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


@app.post('/ocr')
def route_ocr():
    file = request.files.get('file')
    if not file:
        return {'error': 'Missing "file"'}, 400

    options = parse_options(request.form)
    lang = options['lang']
    optimize_images = options['optimize_images']
    save_intermediate = options['save_intermediate']
    intra_block_breaks = options['intra_block_breaks']
    keep_details = options['keep_details']

    config = build_config(options)

    image_paths, infer_file, infer_id = prepare_files([file], optimize=optimize_images, save_intermediate=save_intermediate)

    text = pytesseract.image_to_data(
        infer_file, lang=lang,
        config=' '.join(config),
    )

    for image_path in image_paths:
        os.unlink(image_path)
    if infer_file not in image_paths:
        os.unlink(infer_file)

    pages = process_data([file], text, intra_block_breaks, keep_details)

    return {
        '_usages': [],
        'outcome': None if not pages else pages[0]['blocks'] if keep_details else pages[0]['content'],
    }


@app.post('/ocr-batch')
def route_ocr_batch():
    files = list(request.files.values())
    if not files:
        return {'error': 'Missing files'}, 400

    options = parse_options(request.form)
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

    pages = process_data(files, text, intra_block_breaks, keep_details)

    return {
        '_usages': [],
        'outcome': pages,
    }