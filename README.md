# ABC-Soup - an OCR API

Simple Tesseract 5 API in python, using [tessdata_best](https://github.com/tesseract-ocr/tessdata_best/) and dockerized setup.

Endpoints:

- `GET:/info` get tesseract version and available languages
- `POST:/ocr` perform OCR on a single image, field name `file` for the file
- `POST:/ocr-batch` perform OCR on multiple images, any field name for files (except `options`)

Options for OCR endpoints:

- `optimize_images: true` applies some binarization and contrast optimizations
    - there are quite a few assumptions and todos for better results in [src/helpers/prepare_files.py](./src/helpers/prepare_files.py)
- `save_intermediate: false` stores intermediate image processing files to `/app/shared-assets`
- `intra_block_breaks: true` adds line breaks when text is below each other in a single block
- `keep_details: false` when `true` returns data per page, block and box; when `false` only the combined content per page
- [tesseract](https://tesseract-ocr.github.io/tessdoc) options:
    - `lang` the languages used for inference, defaults to `eng+deu`
    - `psm` when not none passed as `--psm` to tesseract, [see docs](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method)
    - `preserve_interword_spaces` when not none passed as `-c preserve_interword_spaces=` to tesseract

> send options as JSON in field name `options` (serialized additionally, as multipart upload)

For further options and mount points see [docker-compose.yml](docker-compose.yml).

## JS Client Example

Example in Javascript with extra options:

```js
const data = {
    file: file, // the File object from e.g. input
    options: JSON.stringify({keep_details: true}),
}
const formData = new FormData()
for(const file in data) {
    formData.append(file, data[file])
}
// send with e.g. `XMLHttpRequest`
const xhr = new XMLHttpRequest()
xhr.open('POST', 'http://localhost:8730/ocr', true)
xhr.send(formData)
xhr.addEventListener('readystatechange', () => {
    if(xhr.readyState !== 4) return
    if(xhr.status === 200) {
        const result = JSON.parse(xhr.response)
        console.log(result.outcome)
    } else {
        throw new Error('OCR failed')
    }
})
```

## Dev Notes

```shell
pip install -r requirements.txt
```

```shell
docker compose run --rm api bash
```

Models must be saved in `/usr/share/tesseract-ocr/5/tessdata` - thus included in docker image itself, see [Dockerfile](./Dockerfile), for all available best-models see [github.com/tesseract-ocr/tessdata_best](https://github.com/tesseract-ocr/tessdata_best).

> todo: find out how to configure the "init only" config values https://tesseract-ocr.github.io/tessdoc/tess3/ControlParams.html#useful-parameters especially for checking out `load_system_dawg`.

## See also

- [Simple end-2-end flow with potential gotchas demonstrated](https://nanonets.com/blog/ocr-with-tesseract/)
- Example documents found with image search:
    - from https://www.researchgate.net/publication/293322356_Are_Your_Digital_Documents_Web_Friendly_Making_Scanned_Documents_Web_Accessible
        - https://i1.rgstatic.net/publication/293322356_Are_Your_Digital_Documents_Web_Friendly_Making_Scanned_Documents_Web_Accessible/links/574846a408ae2301b0b97d32/largepreview.png
    - from https://www.researchgate.net/publication/307516380_Signature_line_detection_in_scanned_documents
        - https://i1.rgstatic.net/publication/307516380_Signature_line_detection_in_scanned_documents/links/5aa951ef458515178818bc87/largepreview.png

## License

See [LICENSE](LICENSE).
