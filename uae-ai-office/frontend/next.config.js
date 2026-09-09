/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Defaults to Next's usual .next. The override exists so a production
  // build can be verified without overwriting the build directory a
  // running `next dev` is serving from:
  //
  //   NEXT_DIST_DIR=.next-verify npx next build
  //   git checkout next-env.d.ts tsconfig.json   # see below
  //   rm -rf .next-verify
  //
  // That second step is not optional. Next rewrites next-env.d.ts and
  // tsconfig.json to point at whichever distDir is active, so a
  // verification build leaves both generated files aimed at the
  // throwaway directory -- which breaks typechecking against the dev
  // server's own .next once it is deleted. Restore them afterwards.
  //
  // Normal `npm run dev` / `npm run build` behaviour is unchanged.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: "http://127.0.0.1:8000/v1/:path*",
      },
    ];
  },
};

module.exports = nextConfig;

