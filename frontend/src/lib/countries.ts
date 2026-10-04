/** Countries supported by the Meta Ad Library country filter (ISO 3166-1 alpha-2). */
export const COUNTRIES: { code: string; name: string }[] = [
  { code: "ALL", name: "All countries" },
  ...[
    ["US", "United States"], ["GB", "United Kingdom"], ["CA", "Canada"], ["AU", "Australia"], ["NZ", "New Zealand"],
    ["IE", "Ireland"], ["DE", "Germany"], ["FR", "France"], ["ES", "Spain"], ["IT", "Italy"], ["NL", "Netherlands"],
    ["BE", "Belgium"], ["CH", "Switzerland"], ["AT", "Austria"], ["SE", "Sweden"], ["NO", "Norway"], ["DK", "Denmark"],
    ["FI", "Finland"], ["PL", "Poland"], ["PT", "Portugal"], ["CZ", "Czechia"], ["GR", "Greece"], ["RO", "Romania"],
    ["HU", "Hungary"], ["BG", "Bulgaria"], ["HR", "Croatia"], ["SK", "Slovakia"], ["SI", "Slovenia"], ["LT", "Lithuania"],
    ["LV", "Latvia"], ["EE", "Estonia"], ["LU", "Luxembourg"], ["MT", "Malta"], ["CY", "Cyprus"], ["IS", "Iceland"],
    ["UA", "Ukraine"], ["TR", "Türkiye"], ["IL", "Israel"], ["AE", "United Arab Emirates"], ["SA", "Saudi Arabia"],
    ["QA", "Qatar"], ["KW", "Kuwait"], ["EG", "Egypt"], ["MA", "Morocco"], ["NG", "Nigeria"], ["KE", "Kenya"],
    ["ZA", "South Africa"], ["IN", "India"], ["PK", "Pakistan"], ["BD", "Bangladesh"], ["LK", "Sri Lanka"],
    ["SG", "Singapore"], ["MY", "Malaysia"], ["ID", "Indonesia"], ["TH", "Thailand"], ["VN", "Vietnam"],
    ["PH", "Philippines"], ["JP", "Japan"], ["KR", "South Korea"], ["TW", "Taiwan"], ["HK", "Hong Kong"],
    ["BR", "Brazil"], ["MX", "Mexico"], ["AR", "Argentina"], ["CL", "Chile"], ["CO", "Colombia"], ["PE", "Peru"],
  ].map(([code, name]) => ({ code, name })),
];

export function countryName(code: string): string {
  return COUNTRIES.find((c) => c.code === code)?.name ?? code;
}

export function flag(code: string): string {
  if (code.length !== 2) return "🌍";
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}
