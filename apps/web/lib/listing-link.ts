const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

/** Accept a pasted listing link (…/properties/<id>) or a bare listing ID; null if neither. */
export function extractPropertyId(input: string): string | null {
  return input.trim().match(UUID)?.[0].toLowerCase() ?? null;
}
