export function formatRepairLocation(
  building: string,
  floor?: number | null,
  room?: string | null,
): string {
  return [building, floor ? `${floor}层` : '', room || ''].filter(Boolean).join(' ');
}
