import "./globals.css";
export const metadata = {
	title: "Kalshi Event Graph",
	description: "Worldview → Kalshi Event Graph",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
	return (
		<html lang="en">
			<body>{children}</body>
		</html>
	);
}


