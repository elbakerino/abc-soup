# ABC-Soup - an OCR API

[![Github actions Build](https://github.com/elbakerino/abc-soup/actions/workflows/blank.yml/badge.svg)](https://github.com/elbakerino/abc-soup/actions)

Simple Tesseract 5 API in python, using [tessdata_best](https://github.com/tesseract-ocr/tessdata_best/) and dockerized setup.

Endpoints:

- `GET:/info` get tesseract version and available languages
- `POST:/ocr` perform OCR on a single image
- `POST:/ocr-batch` perform OCR on multiple images
- `POST:/ocr-to-pdf` perform OCR on a single image and create a searchable PDF

> Upload the file in the field `file`, the batch endpoint uses all given files. See below [JS Client example](#js-client-example).

Options for OCR endpoints:

- `optimize_images: true` applies some binarization and contrast optimizations
- `save_intermediate: false` stores intermediate image processing files to `/app/shared-assets`
- `intra_block_breaks: true` adds line breaks when text is below each other in a single block (except PDF endpoint)
- `keep_details: false` when `true` returns data per page, block and box; when `false` only the combined content per page (except PDF endpoint)
- [tesseract](https://tesseract-ocr.github.io/tessdoc) options:
    - `lang` the languages used for inference, defaults to `eng+deu`
    - `psm` when not none passed as `--psm` to tesseract, [see docs](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html#page-segmentation-method)
    - `preserve_interword_spaces` when not none passed as `-c preserve_interword_spaces=` to tesseract

> Options: send options as JSON in field name `options` (serialized additionally, as multipart upload).
>
> Image optimizations: in [helpers/optimize_image.py](./src/helpers/optimize_image.py) are a few input-quality assumptions noted and (open) todos which may yield better results.

For further options and mount points checkout [the docker example](#docker-example).

## Docker Example

The ready to use docker image includes models `eng` and `deu`:

```yaml
# docker-compose.yml
services:
    abc-soup:
        image: ghcr.io/elbakerino/abc-soup:0.0.3
        environment:
            PORT: 80
            APP_ENV: local
            #GUN_W: 2 # control gunicorn workers
            #DEFAULT_LANG: deu+eng # control the default `lang` for tesseract
        volumes:
            - ./shared-data:/app/shared-assets
        ports:
            - "8730:80"
```

Models must be saved in `/usr/share/tesseract-ocr/5/tessdata` - thus included in docker image itself, see [Dockerfile](./Dockerfile), for all available best-models see [github.com/tesseract-ocr/tessdata_best](https://github.com/tesseract-ocr/tessdata_best).

> todo: find out how to configure the "init only" config values https://tesseract-ocr.github.io/tessdoc/tess3/ControlParams.html#useful-parameters especially for checking out `load_system_dawg`.

## JS Client Example

Example in Javascript with extra options:

```js
const data = {
    file: file, // the File object from e.g. input field
    options: JSON.stringify({
        keep_details: true,
        lang: 'eng+deu',
        psm: 4,
    }),
}
const formData = new FormData()
for(const prop in data) {
    formData.append(prop, data[prop])
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

Install deps for IDE support (or set up a remote interpreter):

```shell
pip install -r requirements.txt
```

Start the dev-server with docker compose:

```shell
docker compose up

# or go into the container:
# docker compose run --rm api bash
```

Notice that the image requires rebuilding when changing e.g. deps:

```shell
docker compose up --build
# or:
# docker compose build
```

## See also

- [Simple end-2-end flow with potential gotchas demonstrated](https://nanonets.com/blog/ocr-with-tesseract/)
- Example documents found with image search:
    - from https://www.researchgate.net/publication/293322356_Are_Your_Digital_Documents_Web_Friendly_Making_Scanned_Documents_Web_Accessible
        - https://i1.rgstatic.net/publication/293322356_Are_Your_Digital_Documents_Web_Friendly_Making_Scanned_Documents_Web_Accessible/links/574846a408ae2301b0b97d32/largepreview.png
    - from https://www.researchgate.net/publication/307516380_Signature_line_detection_in_scanned_documents
        - https://i1.rgstatic.net/publication/307516380_Signature_line_detection_in_scanned_documents/links/5aa951ef458515178818bc87/largepreview.png

## License

See [LICENSE](LICENSE).
