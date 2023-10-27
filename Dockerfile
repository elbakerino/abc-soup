FROM python:3.10-slim-bookworm AS builder

ENV PYTHONUNBUFFERED 1
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update &&  \
    apt-get install -y --no-install-recommends \
    libssl-dev curl \
    tesseract-ocr \
    ffmpeg libsm6 libxext6 \
    libgl1 \
    libglib2.0-0 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/share/tesseract-ocr/5/tessdata/eng.traineddata

WORKDIR /app

# not changable folder - seems to be tesseract compile time var
# full string path as ADD has some strange behaviour if target path contains variables
# todo: ADD somehow only adds 1byte files
#ADD https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata /usr/share/tesseract-ocr/5/tessdata/eng.traineddata
RUN cd /usr/share/tesseract-ocr/5/tessdata && curl -O https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata
RUN cd /usr/share/tesseract-ocr/5/tessdata && curl -O https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/deu.traineddata

COPY requirements.txt requirements.txt

FROM builder AS dev

RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

CMD python -m flask --app src/server --debug run --host 0.0.0.0 --port ${PORT}

FROM builder

RUN pip install --no-cache-dir --upgrade gunicorn

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY ./src /app/src

ENV GUN_W 2

CMD cd src && python -m gunicorn -w ${GUN_W} server:app
