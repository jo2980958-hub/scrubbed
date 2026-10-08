/** Format pence as pounds sterling, e.g. 24000 -> "£240.00". */
export function pounds(pence: number | null | undefined): string {
  const p = Number(pence ?? 0);
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    minimumFractionDigits: 2,
  }).format(p / 100);
}

/** Short form without pence, e.g. 24000 -> "£240". */
export function poundsShort(pence: number | null | undefined): string {
  const p = Number(pence ?? 0);
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    maximumFractionDigits: 0,
  }).format(p / 100);
}
