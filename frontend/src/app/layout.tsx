/**
 * src/app/layout.tsx
 * --------------------
 * Root layout -- mostly boilerplate. Sets the page metadata and pulls in
 * globals.css. You likely don't need to change much here.
 */

import "./globals.css";

export const metadata = {
  title: "OmniCommand",
  description: "Real-time urban risk decision intelligence",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
