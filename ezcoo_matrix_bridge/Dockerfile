ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 PYTHONUNBUFFERED=1

RUN apk add --no-cache python3 py3-pip \
 && (pip3 install --no-cache-dir --break-system-packages "paho-mqtt>=1.6,<3" "pyserial>=3.5" \
     || pip3 install --no-cache-dir "paho-mqtt>=1.6,<3" "pyserial>=3.5")

COPY run.sh /run.sh
COPY ezcoo_bridge.py /ezcoo_bridge.py
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
