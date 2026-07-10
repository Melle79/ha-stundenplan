ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

COPY rootfs/app/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY rootfs/app /app
COPY rootfs/card /card
COPY rootfs/run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD [ "/run.sh" ]
