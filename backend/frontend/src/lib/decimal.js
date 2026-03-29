/**
 * KES amount formatting utilities.
 * All monetary display goes through these functions — never raw numbers.
 */

export function formatKES(amount, opts = {}) {
  const value = parseFloat(String(amount ?? '0'))
  if (isNaN(value)) return 'KES —'

  const { compact = false, showCents = true } = opts

  if (compact) {
    if (Math.abs(value) >= 1_000_000) return `KES ${(value / 1_000_000).toFixed(1)}M`
    if (Math.abs(value) >= 1_000) return `KES ${(value / 1_000).toFixed(1)}K`
  }

  return `KES ${value.toLocaleString('en-KE', {
    minimumFractionDigits: showCents ? 2 : 0,
    maximumFractionDigits: showCents ? 2 : 0,
  })}`
}

export function formatChange(value) {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${formatKES(value)}`
}