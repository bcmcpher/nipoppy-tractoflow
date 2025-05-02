FROM scilus/scilus-flows:1.5.0

# install the code
RUN mkdir -p /opt/tf-wrapper
COPY ./tf-wrapper /opt/tf-wrapper
RUN chmod -R 775 /opt/tf-wrapper

# install pybids?
RUN pip install --upgrade pip
RUN pip install pybids jsonschema

# set run command to call the script
ENTRYPOINT ["/opt/tf-wrapper/run-tractoflow.sh"]
