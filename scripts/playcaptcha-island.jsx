import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { ClawCaptcha } from "playcaptcha";

const mounts = new Map();

function CaptchaIsland({ title, assetBase, onVerified }) {
  const [verified, setVerified] = useState(false);

  return (
    <ClawCaptcha
      assetBase={assetBase}
      title={verified ? "验证已完成" : title}
      onVerify={() => {
        setVerified(true);
        onVerified?.();
      }}
    />
  );
}

function render(entry) {
  entry.root.render(
    <CaptchaIsland
      key={entry.version}
      assetBase={entry.assetBase}
      title={entry.title}
      onVerified={entry.onVerified}
    />,
  );
}

window.orbitPlayCaptcha = {
  mount({ element, mode, title = "抓到正确玩具完成验证", assetBase = "/playcaptcha/assets/toys/", onVerified }) {
    if (!element || !mode) return;
    const current = mounts.get(mode);
    const entry = current || {
      root: createRoot(element),
      version: 0,
      assetBase,
      title,
      onVerified,
    };
    entry.assetBase = assetBase;
    entry.title = title;
    entry.onVerified = onVerified;
    mounts.set(mode, entry);
    render(entry);
  },
  reset(mode) {
    const entry = mounts.get(mode);
    if (!entry) return;
    entry.version += 1;
    render(entry);
  },
};

window.dispatchEvent(new CustomEvent("orbit:playcaptcha-ready"));
