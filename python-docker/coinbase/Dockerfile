# set base image (host OS)
FROM python:3.8

# set the working directory in the container
WORKDIR /app

# copy all the contents in the current dir to the container dir (requirements.txt, credentials/ , track.py)
COPY . .

# install dependencies
RUN pip install -r requirements.txt

# command to run on container start
CMD [ "python", "./track.py" ]