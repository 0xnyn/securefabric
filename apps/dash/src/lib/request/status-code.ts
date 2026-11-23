export function getStatusColor(
	value: number
): Record<"text" | "bg" | "border", string> {
	if (value < 100 || value >= 600) {
		return {
			bg: "bg-gray-100 dark:bg-gray-900/50",
			border: "border-gray-200 dark:border-gray-800",
			text: "text-gray-500",
		};
	}
	switch (value.toString().charAt(0)) {
		case "1":
			return {
				bg: "bg-blue-100 dark:bg-blue-900/50",
				border: "border-blue-200 dark:border-blue-800",
				text: "text-blue-500",
			};
		case "2":
			return {
				bg: "bg-green-100 dark:bg-green-900/50",
				border: "border-green-200 dark:border-green-800",
				text: "text-green-500",
			};
		case "3":
			return {
				bg: "bg-yellow-100 dark:bg-yellow-900/50",
				border: "border-yellow-200 dark:border-yellow-800",
				text: "text-yellow-500",
			};
		case "4":
			return {
				bg: "bg-orange-100 dark:bg-orange-900/50",
				border: "border-orange-200 dark:border-orange-800",
				text: "text-orange-500",
			};
		case "5":
			return {
				bg: "bg-red-100 dark:bg-red-900/50",
				border: "border-red-200 dark:border-red-800",
				text: "text-red-500",
			};
		default:
			return {
				bg: "bg-gray-100 dark:bg-gray-900/50",
				border: "border-gray-200 dark:border-gray-800",
				text: "text-gray-500",
			};
	}
}
