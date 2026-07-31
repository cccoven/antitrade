import MarkdownDocument from "@/components/markdown/MarkdownDocument";
import MarkdownRenderer from "@/components/markdown/MarkdownRenderer";

interface Props {
  title: string;
  tags: string[];
  body: string;
}

export default function StrategyView({ title, tags, body }: Props) {
  return (
    <MarkdownDocument title={title} fallbackTitle="Untitled" tags={tags}>
      <MarkdownRenderer text={body} />
    </MarkdownDocument>
  );
}
