import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

const components: Components = {
  a: ({ children, href }) => (
    <a
      className="font-bold text-[#86d9f0] underline decoration-[#4e849f] underline-offset-3 transition-colors hover:text-[#b8f2ff]"
      href={href}
      rel="noreferrer noopener"
      target="_blank"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-3 border-[#5f9fb4] bg-[#14243a]/55 py-2 pr-3 pl-4 text-[#b9c8d8]">
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => (
    <code
      className={`${className ?? ""} rounded border border-[#304865] bg-[#14243a] px-1.5 py-0.5 font-mono text-[0.9em] text-[#bfe8f5]`}
    >
      {children}
    </code>
  ),
  h1: ({ children }) => (
    <h1 className="mt-5 mb-2 text-[1.25rem] leading-[1.4] font-bold">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 text-[1.125rem] leading-[1.45] font-bold">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 mb-2 text-[1rem] leading-[1.5] font-bold">{children}</h3>
  ),
  li: ({ children }) => <li className="my-1 pl-1">{children}</li>,
  ol: ({ children }) => <ol className="my-3 list-decimal pl-6">{children}</ol>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl border border-[#344b68] bg-[#0d1625] p-4 text-[0.84rem] leading-[1.65] text-[#dceaf7] shadow-inner shadow-black/25 [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-left text-[0.9rem]">{children}</table>
    </div>
  ),
  td: ({ children }) => <td className="border border-[#34445b] px-3 py-2">{children}</td>,
  th: ({ children }) => (
    <th className="border border-[#425873] bg-[#1e304a] px-3 py-2 text-[#e3effa]">{children}</th>
  ),
  ul: ({ children }) => <ul className="my-3 list-disc pl-6">{children}</ul>,
}

export function MarkdownContent({
  className = "",
  content,
}: {
  className?: string
  content: string
}) {
  return (
    <div className={className}>
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
