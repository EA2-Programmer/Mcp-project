import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
    output: 'export', // This is the magic line for static sites
  images: {
    unoptimized: true, // Required because GitLab won't run the Next.js image optimization server
  },

};

export default nextConfig;
