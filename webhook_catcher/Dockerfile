FROM debian:stable-slim

RUN set -eux; apt-get update; apt-get install -y --no-install-recommends python3

RUN useradd -ms /bin/bash catcheruser

USER catcheruser
WORKDIR /home/catcheruser

COPY catcher.py ./

EXPOSE 8080
#ENTRYPOINT python3 /home/catcheruser/catcher.py
CMD ["python3","-u", "/home/catcheruser/catcher.py"]
