/** The API's limit for the first message. */
export const ASK_MAX_CHARS = 2000;

export interface QuickQuestion {
  key: string;
  text: string;
}

/**
 * The first message of an "Ask the owner" chat: the chosen quick questions (in the list's order,
 * one per line), then the person's own words. Empty when there is nothing to send. `questions`
 * is LISTING_QUICK_QUESTIONS from @flatmate/contracts.
 */
export function composeOwnerQuestion(
  questions: readonly QuickQuestion[],
  chosen: readonly string[],
  ownText: string,
): string {
  const lines = questions.filter((q) => chosen.includes(q.key)).map((q) => q.text);
  const own = ownText.trim();
  if (own) lines.push(own);
  return lines.join("\n");
}
