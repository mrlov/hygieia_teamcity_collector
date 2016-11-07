FROM python:3
MAINTAINER "Alexey Anikanov"
ADD https://github.com/SurveyMonkey/pyteamcity/archive/master.zip /pyteamcity.zip
RUN apt-get update -y && apt-get install -y unzip
RUN unzip /pyteamcity.zip
RUN cd pyteamcity-master && python3 setup.py install
ADD main.py /main.py
EXPOSE 80
CMD ["python3","/main.py"]
