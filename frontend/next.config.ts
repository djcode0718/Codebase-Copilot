import os from 'node:os';
import type { NextConfig } from "next";

function isPrivateIpv4(address: string): boolean {
  return (
    address.startsWith('10.') ||
    address.startsWith('192.168.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(address)
  );
}

function collectAllowedDevOrigins(): string[] {
  const origins = new Set<string>(['localhost', '127.0.0.1', '::1']);

  const envOrigins = [
    process.env.NEXT_PUBLIC_DEV_ORIGIN_HOST,
    process.env.DEV_ORIGIN_HOST,
    process.env.DEV_ALLOWED_ORIGINS,
  ]
    .flatMap((value) => (value ?? '').split(','))
    .map((value) => value.trim())
    .filter(Boolean);

  for (const origin of envOrigins) {
    origins.add(origin);
  }

  for (const interfaces of Object.values(os.networkInterfaces())) {
    for (const address of interfaces ?? []) {
      if (address.family === 'IPv4' && !address.internal && isPrivateIpv4(address.address)) {
        origins.add(address.address);
      }
    }
  }

  return [...origins];
}

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: collectAllowedDevOrigins(),
};

export default nextConfig;
