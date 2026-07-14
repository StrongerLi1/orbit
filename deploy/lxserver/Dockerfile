FROM docker.m.daocloud.io/library/alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc AS source

ARG LXSERVER_COMMIT=0d653bf31b19635dd20299c5b341630b426c79f3
ARG LXSERVER_SHA256=9d332efacd8d3d1c10fa06de795a00023949a73072815be9461ab19c5f1084cd
WORKDIR /source
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories \
    && apk add --no-cache curl tar \
    && curl -fsSL "https://github.com/XCQ0607/lxserver/archive/${LXSERVER_COMMIT}.tar.gz" -o source.tar.gz \
    && echo "${LXSERVER_SHA256}  source.tar.gz" | sha256sum -c - \
    && tar -xzf source.tar.gz --strip-components=1 \
    && rm source.tar.gz

FROM docker.m.daocloud.io/library/node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS builder
WORKDIR /source
COPY --from=source /source/ ./
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories \
    && apk add --no-cache g++ make python3 \
    && (apk add --no-cache chromaprint || true) \
    && npm install --ignore-scripts --no-audit --no-fund \
    && npm install --save-exact --ignore-scripts --no-audit --no-fund ws@8.21.0 \
    && npm audit --omit=dev --audit-level=high \
    && npm run build \
    && rm -rf node_modules \
    && npm install --omit=dev --no-audit --no-fund \
    && npm audit --omit=dev --audit-level=high \
    && node -e "process.exit(require('ws/package.json').version === '8.21.0' ? 0 : 1)" \
    && mkdir /build-output \
    && mv server node_modules config.js index.js package.json public /build-output/

FROM docker.m.daocloud.io/library/node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2
WORKDIR /server
RUN sed -i 's|dl-cdn.alpinelinux.org|mirrors.aliyun.com|g' /etc/apk/repositories \
    && (apk add --no-cache chromaprint || true) \
    && addgroup -S -g 10001 lx \
    && adduser -S -D -H -u 10001 -G lx lx
COPY --from=builder --chown=10001:10001 /build-output/ ./

ENV NODE_ENV=production \
    PORT=9527 \
    BIND_IP=0.0.0.0 \
    DATA_PATH=/server/data \
    LOG_PATH=/server/logs
EXPOSE 9527
USER lx
CMD ["node", "index.js"]
