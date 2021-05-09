FROM flant/shell-operator:v1.0.1 as BUILD
RUN apk add upx; upx -9 /usr/bin/jq /shell-operator

FROM alpine:3.13
# Put back original content
COPY --from=BUILD /usr/bin/jq /usr/bin/jq
COPY --from=BUILD /shell-operator /shell-operator
COPY --from=BUILD /shell_lib.sh /shell_lib.sh
COPY --from=BUILD /frameworks /frameworks
ADD hooks /hooks

# Install python deps
RUN apk add --no-cache  tini \
                        python3 \
                        py3-pip \
                        py3-jinja2 \
                        # Kubernetes client deps \
                        py3-yaml \
                        py3-six \
                        py3-certifi \
                        py3-dateutil \
                        py3-setuptools \
                        py3-google-auth \
                        py3-requests \
                        py3-requests-oauthlib \
                        py3-websocket-client \
                        py3-urllib3 && \
    pip install kubernetes

WORKDIR /
ENV SHELL_OPERATOR_HOOKS_DIR /hooks
ENV LOG_TYPE json
ENTRYPOINT ["/sbin/tini", "--", "/shell-operator"]
CMD ["start"]
