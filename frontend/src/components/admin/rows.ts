import type { InventoryItem, NetworkStatus, PhcRow } from '../../types/api'

export interface Row {
  key: string
  phc: PhcRow
  item: InventoryItem
}

/** One row per PHC x medicine, most urgent first. */
export function flatten(data: NetworkStatus | null): Row[] {
  if (!data) return []
  const rows = data.phcs.flatMap((phc) =>
    phc.inventory.map((item) => ({ key: `${phc.phc_id}__${item.medicine_name}`, phc, item })),
  )
  return rows.sort((a, b) => a.item.days_to_stockout - b.item.days_to_stockout)
}

export function formatDays(d: number): string {
  return d >= 999 ? '999+' : d.toFixed(1)
}