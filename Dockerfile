FROM python:3.10-slim-bookworm AS builder

ENV PYTHONUNBUFFERED 1
ARG DEBIAN_FRONTEND=noninteractive

RUN pip install --upgrade pip

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-numpy python3-pandas \
    libssl-dev curl

RUN apt-get update &&  \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ffmpeg libsm6 libxext6 \
    libgl1 \
    libglib2.0-0

WORKDIR /app

# not changable folder - seems to be tesseract compile time var
# full string path as ADD has some strange behaviour if target path contains variables
# todo: ADD somehow only adds 1byte files
#ADD https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata /usr/share/tesseract-ocr/5/tessdata/eng.traineddata
RUN cd /usr/share/tesseract-ocr/5/tessdata && curl -O https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/eng.traineddata
RUN cd /usr/share/tesseract-ocr/5/tessdata && curl -O https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/deu.traineddata

COPY requirements.txt requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

CMD python -m flask --app src/server --debug run --host 0.0.0.0 --port ${PORT}
