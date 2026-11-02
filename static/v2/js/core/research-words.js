// Reader-facing words for the research framework's internal labels (advice policy, 2026-10-29).
// The labels still drive the server's logic ("Avoid" caps a grade); a reader is told what the rules found
// instead of "Avoid", "Not Investable", "High Conviction" or "Attractive", which read as instructions or
// endorsements. app/research/words.py holds the same tables and tests/test_ai_policy.py keeps them equal.

export const SETUP_GRADE = { S: 'Grade S', A: 'Grade A', B: 'Grade B', Avoid: 'No setup' };
export const CONVICTION = {
  'High Conviction': 'strong on the long-term rules',
  Constructive: 'positive on the long-term rules',
  Neutral: 'neutral on the long-term rules',
  'Weak Structure': 'weak on the long-term rules',
  'Not Investable': 'fails the long-term rules',
};
export const VALUATION = { Attractive: 'Cheap', Fair: 'Fair', Full: 'Full', Stretched: 'Expensive' };

export const setupGrade = (g) => SETUP_GRADE[String(g || '')] || String(g || '');
export const convictionPhrase = (l) => CONVICTION[String(l || '')] || String(l || '').toLowerCase();
export const valuationWord = (l) => VALUATION[String(l || '')] || String(l || '');
