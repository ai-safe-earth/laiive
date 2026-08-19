import DOMPurify from "dompurify";

/**
 * The composer writes prose, not HTML, but it does use markdown-lite for
 * emphasis and the occasional link. Anything else is escaped by the sanitizer.
 */
export function Markdown({ text, className }: { text: string; className?: string }) {
  const html = DOMPurify.sanitize(
    text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(
        /\[(.*?)\]\((.*?)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">$1</a>',
      ),
    { ALLOWED_TAGS: ["strong", "a"], ALLOWED_ATTR: ["href", "target", "rel", "class"] },
  );

  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
