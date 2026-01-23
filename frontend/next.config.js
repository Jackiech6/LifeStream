/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://4wq95qxnmb.execute-api.us-east-1.amazonaws.com/staging',
  },
}

module.exports = nextConfig
