import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import MarkdownEditor from "@/components/markdown/MarkdownEditor";
import { Input } from "@/components/ui/input";
import { inputStyle } from "../strategies-ui-config";
import TagPicker from "./TagPicker";

interface Props {
  title: string;
  body: string;
  tags: string[];
  tagSuggestions?: string[];
  onTitleChange: (v: string) => void;
  onBodyChange: (v: string) => void;
  onTagsChange: (v: string[]) => void;
  autoFocusTitle?: boolean;
}

export default function StrategyEditor({
  title, body, tags, tagSuggestions = [],
  onTitleChange, onBodyChange, onTagsChange,
  autoFocusTitle,
}: Props) {
  const { t } = useTranslation();
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocusTitle) titleRef.current?.focus();
  }, [autoFocusTitle]);

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-3">
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-card/40 p-4 shadow-sm">
        <Input
          ref={titleRef}
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder={t("strategies.titlePlaceholder")}
          style={inputStyle}
          className="border-transparent bg-transparent px-1 font-medium shadow-none focus-visible:border-transparent focus-visible:ring-0"
        />
        <TagPicker
          value={tags}
          onChange={onTagsChange}
          suggestions={tagSuggestions}
        />
      </div>
      <MarkdownEditor
        value={body}
        onChange={onBodyChange}
        placeholder={t("strategies.bodyPlaceholder")}
      />
    </div>
  );
}
