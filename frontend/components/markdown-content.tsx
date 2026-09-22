import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

const components: Components = {
  a: ({ children, href }) => (
    <a
      className="font-bold text-[#3f5f89] underline decoration-[#9eb3cc] underline-offset-3"
      href={href}
      rel="noreferrer noopener"
      target="_blank"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-3 border-[#c9bd7b] pl-4 text-[#61605b]">
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => (
    <code
      className={`${className ?? ""} rounded bg-[#efeee9] px-1.5 py-0.5 font-mono text-[0.9em]`}
    >
      {children}
    </code>
  ),
  h1: ({ children }) => <h3 className="mt-5 mb-2 text-[1.08rem] font-extrabold">{children}</h3>,
  h2: ({ children }) => <h4 className="mt-5 mb-2 text-[1.02rem] font-extrabold">{children}</h4>,
  h3: ({ children }) => <h5 className="mt-4 mb-2 font-extrabold">{children}</h5>,
  li: ({ children }) => <li className="my-1 pl-1">{children}</li>,
  ol: ({ children }) => <ol className="my-3 list-decimal pl-6">{children}</ol>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl bg-[#292925] p-4 text-[0.84rem] leading-[1.65] text-[#f7f7f2] [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-left text-[0.9rem]">{children}</table>
    </div>
  ),
  td: ({ children }) => <td className="border border-[#deddd7] px-3 py-2">{children}</td>,
  th: ({ children }) => (
    <th className="border border-[#deddd7] bg-[#f6f5f1] px-3 py-2">{children}</th>
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
