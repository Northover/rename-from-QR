FROM python:3.7.6-alpine

VOLUME /app
WORKDIR /app

COPY . /app

RUN apk add --no-cache libzbar zbar-dev openjpeg-dev jpeg-dev py3-pillow binutils
RUN pip install -r requirements.txt
RUN pip install pyinstaller

RUN apk add --no-cache musl-dev

RUN ln -fs /lib/libc.musl-x86_64.so.1 /usr/bin/ldd

ENTRYPOINT ["pyinstaller"]
