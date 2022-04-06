FROM python:3-onbuild

WORKDIR /usr/app/src

RUN pip install p2pnetwork

COPY . ./

CMD [ "python","-u","./server.py"]