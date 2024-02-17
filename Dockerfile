FROM alpine:3.19.0

RUN apk update && apk add py3-pip py3-virtualenv
WORKDIR /home/app/
COPY . .
RUN adduser -D ptb && chown -R ptb:ptb /home/app

USER ptb
RUN virtualenv venv
RUN ./venv/bin/pip install --no-cache-dir -r requirements.txt
CMD [ "/home/app/venv/bin/python", "/home/app/app.py" ]
