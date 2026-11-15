FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
	curl \
	socat \
	wget \
	python3 \
	iproute2 \
	iputils-ping \
	netcat-traditional \
	nmap \
	procps \
	apt-transport-https \
	software-properties-common


RUN wget -q "https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb" && \
    dpkg -i packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y powershell

CMD ["/bin/bash"]
