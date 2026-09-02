const numberFormatter = new Intl.NumberFormat('en-NP')

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat('en-NP', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function formatNpr(value: number, fractionDigits = 2): string {
  return new Intl.NumberFormat('en-NP', {
    style: 'currency',
    currency: 'NPR',
    currencyDisplay: 'code',
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value)
}

export function formatCompactNpr(value: number): string {
  return new Intl.NumberFormat('en-NP', {
    style: 'currency',
    currency: 'NPR',
    currencyDisplay: 'code',
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatPercentage(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, 2)}%`
}

export function formatSignedNumber(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, 2)}`
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en-NP', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function formatInteger(value: number): string {
  return numberFormatter.format(value)
}

export function getChangeTone(value: number): 'positive' | 'negative' | 'neutral' {
  if (value > 0) {
    return 'positive'
  }

  if (value < 0) {
    return 'negative'
  }

  return 'neutral'
}
