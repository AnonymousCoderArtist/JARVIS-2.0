import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { CodeBlock } from "@/components/CodeBlock";
import { cn } from "@/lib/utils";

import "katex/dist/katex.min.css";

interface MarkdownTextRendererProps {
  children: string;
  className?: string;
}

function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-4 overflow-x-auto rounded-lg border" style={{ borderColor: "rgba(26, 90, 255, 0.25)" }}>
      <table
        className="w-full border-collapse"
      >
        {children}
      </table>
    </div>
  );
}

function TableHead({ children }: { children: React.ReactNode }) {
  return (
    <thead>
      <tr style={{ background: "rgba(26, 90, 255, 0.15)" }}>
        {children}
      </tr>
    </thead>
  );
}

function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

function TableRow({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b" style={{ borderColor: "rgba(26, 90, 255, 0.1)" }}>
      {children}
    </tr>
  );
}

function TableCell({ children, isHeader = false }: { children: React.ReactNode; isHeader?: boolean }) {
  const Tag = isHeader ? "th" : "td";
  return (
    <Tag
      className="px-3 py-2 text-sm"
      style={{
        color: isHeader ? "rgba(200, 220, 255, 0.95)" : "rgba(180, 200, 230, 0.85)",
        fontWeight: isHeader ? 600 : 400,
      }}
    >
      {children}
    </Tag>
  );
}

/**
 * Heavy markdown stack (GFM, math, KaTeX, syntax highlighting) kept in a
 * separate chunk so the app shell can paint sooner on refresh.
 */
export default function MarkdownTextRenderer({
  children,
  className,
}: MarkdownTextRendererProps) {
  return (
    <div
      className={cn(
        "markdown-content prose prose-lg max-w-none dark:prose-invert",
        "prose-headings:mt-4 prose-headings:mb-2 prose-headings:font-semibold prose-headings:tracking-tight",
        "prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-h4:text-sm",
        "prose-p:my-2",
        "prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5",
        "prose-blockquote:my-3 prose-blockquote:border-l-2 prose-blockquote:font-normal",
        "prose-blockquote:not-italic prose-blockquote:text-foreground/80",
        "prose-a:text-primary prose-a:underline-offset-2 hover:prose-a:opacity-80",
        "prose-hr:my-6",
        "prose-pre:my-0 prose-pre:bg-transparent prose-pre:p-0",
        "prose-code:before:content-none prose-code:after:content-none prose-code:font-normal",
        className,
      )}
      style={{ lineHeight: "var(--cjk-line-height)" }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          code({ className: cls, children: kids, ...props }) {
            const match = /language-(\w+)/.exec(cls || "");
            if (!match) {
              return (
                <code
                  className={cn(
                    "rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]",
                    cls,
                  )}
                  {...props}
                >
                  {kids}
                </code>
              );
            }
            const code = String(kids).replace(/\n$/, "");
            return <CodeBlock language={match[1]} code={code} className="my-3" />;
          },
          pre({ children: markdownChildren }) {
            return <>{markdownChildren}</>;
          },
          a({ href, children: markdownChildren, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary underline underline-offset-2 hover:opacity-80"
                {...props}
              >
                {markdownChildren}
              </a>
            );
          },
          table({ children }) {
            return <Table>{children}</Table>;
          },
          thead({ children }) {
            return <TableHead>{children}</TableHead>;
          },
          tbody({ children }) {
            return <TableBody>{children}</TableBody>;
          },
          tr({ children }) {
            return <TableRow>{children}</TableRow>;
          },
          th({ children }) {
            return <TableCell isHeader>{children}</TableCell>;
          },
          td({ children }) {
            return <TableCell>{children}</TableCell>;
          },
          p({ children }) {
            return (
              <p className="my-2" style={{ color: "rgba(180, 200, 230, 0.9)" }}>
                {children}
              </p>
            );
          },
          h1({ children }) {
            return (
              <h1 className="text-xl font-semibold mt-4 mb-2" style={{ color: "rgba(200, 220, 255, 0.95)" }}>
                {children}
              </h1>
            );
          },
          h2({ children }) {
            return (
              <h2 className="text-lg font-semibold mt-4 mb-2" style={{ color: "rgba(200, 220, 255, 0.95)" }}>
                {children}
              </h2>
            );
          },
          h3({ children }) {
            return (
              <h3 className="text-base font-semibold mt-3 mb-1" style={{ color: "rgba(200, 220, 255, 0.95)" }}>
                {children}
              </h3>
            );
          },
          ul({ children }) {
            return (
              <ul className="my-2 ml-4 list-disc" style={{ color: "rgba(180, 200, 230, 0.85)" }}>
                {children}
              </ul>
            );
          },
          ol({ children }) {
            return (
              <ol className="my-2 ml-4 list-decimal" style={{ color: "rgba(180, 200, 230, 0.85)" }}>
                {children}
              </ol>
            );
          },
          li({ children }) {
            return (
              <li className="my-1" style={{ color: "rgba(180, 200, 230, 0.85)" }}>
                {children}
              </li>
            );
          },
          strong({ children }) {
            return (
              <strong style={{ color: "rgba(200, 220, 255, 0.95)", fontWeight: 600 }}>
                {children}
              </strong>
            );
          },
          em({ children }) {
            return (
              <em style={{ color: "rgba(180, 200, 230, 0.85)" }}>
                {children}
              </em>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
