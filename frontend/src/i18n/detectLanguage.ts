/**
 * Simple language detection based on common indicator words.
 * Shared between Chat and PromoterCreate pages.
 */
export function detectLanguageFromText(text: string): string | null {
  const spanishIndicators = /\b(hola|qué|dónde|cuándo|cómo|quiero|busco|hay|para|esta|esta noche|cerca|evento|música|concierto)\b/i;
  const italianIndicators = /\b(ciao|dove|quando|come|voglio|cerco|c'è|per|questa|stasera|vicino|evento|musica|concerto)\b/i;
  const catalanIndicators = /\b(hola|què|on|quan|com|vull|busco|hi ha|per|aquesta|avui|prop|esdeveniment|música|concert)\b/i;
  const englishIndicators = /\b(hello|hi|what|where|when|how|want|looking|is there|for|this|tonight|near|event|music|concert)\b/i;

  if (spanishIndicators.test(text)) return 'es';
  if (italianIndicators.test(text)) return 'it';
  if (catalanIndicators.test(text)) return 'ca';
  if (englishIndicators.test(text)) return 'en';

  return null;
}
