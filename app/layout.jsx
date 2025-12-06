import './globals.css'

export const metadata = {
  title: 'Black Tie Orders',
  description: 'Production Order System for Black Tie Cannabis',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
