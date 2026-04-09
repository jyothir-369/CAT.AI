import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable React strict mode for better DX
  reactStrictMode: true,

  // Output standalone for Docker deployment
  output: "standalone",

  // Forward API calls to the FastAPI backend during dev
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },

  // Image domains
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
      {
        protocol: "https",
        hostname: "*.s3.amazonaws.com",
      },
    ],
  },

  experimental: {
    // Server components fetch caching
    serverComponentsExternalPackages: [],
  },
};

export default nextConfig;