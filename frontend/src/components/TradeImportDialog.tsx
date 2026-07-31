import { useMemo, useRef, useState } from "react";
import { AlertCircle, FileSpreadsheet, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  commitTradeImport,
  prepareTradeImport,
  reviseTradeImport,
  type TradeImportDraft,
} from "@/api/trade-imports";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/Toast";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

const ACCEPT = "image/png,image/jpeg,image/webp,.csv,.xlsx,.json";
const controlStyle = { fontSize: "var(--font-ui)" };
const TRADE_FIELDS = [
  "symbol", "direction", "open_price", "close_price", "quantity",
  "open_time", "close_time", "fees", "pnl",
];
const FILL_FIELDS = [
  "symbol", "side", "price", "quantity", "executed_at",
  "fees", "external_id", "account_ref", "currency",
];

export default function TradeImportDialog({ open, onClose, onImported }: Props) {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [draft, setDraft] = useState<TradeImportDraft | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const columns = useMemo(
    () => Object.keys(draft?.rows[0]?.raw_data ?? {}),
    [draft],
  );
  const fields = draft?.rows.some((row) => row.record_kind === "fill")
    ? FILL_FIELDS
    : TRADE_FIELDS;

  const close = () => {
    if (!loading) onClose();
  };

  const prepare = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const next = await prepareTradeImport(file);
      setDraft(next);
      setMapping(next.mapping);
    } finally {
      setLoading(false);
    }
  };

  const recompute = async () => {
    if (!draft) return;
    setLoading(true);
    try {
      const next = await reviseTradeImport(draft.id, mapping);
      setDraft(next);
      setMapping(next.mapping);
    } finally {
      setLoading(false);
    }
  };

  const commit = async () => {
    if (!draft) return;
    setLoading(true);
    try {
      const next = await commitTradeImport(draft.id);
      setDraft(next);
      showToast(t("tradeImport.committed", {
        count: next.summary.created_trades ?? 0,
      }), "success");
      setFile(null);
      setDraft(null);
      setMapping({});
      onImported();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) close(); }}>
      <DialogContent showCloseButton={false} className="sm:max-w-[900px]">
        <DialogHeader>
          <DialogTitle>{t("tradeImport.title")}</DialogTitle>
        </DialogHeader>

        {!draft ? (
          <div className="space-y-3">
            <div
              className={cn(
                "flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-[12px] border border-dashed border-border bg-muted/20 p-6 transition-colors hover:bg-muted/35",
                dragOver && "border-primary bg-primary/5",
              )}
              role="button"
              tabIndex={0}
              onClick={() => inputRef.current?.click()}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
              }}
              onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragOver(false);
                const next = event.dataTransfer.files[0];
                if (next) setFile(next);
              }}
            >
              <Upload className="size-[var(--icon-lg)] text-muted-foreground" />
              <p className="mt-2 text-ui text-foreground">{t("tradeImport.drop")}</p>
              <p className="mt-1 text-caption text-muted-foreground">
                CSV, XLSX, JSON, PNG, JPG, WEBP
              </p>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(event) => {
                  const next = event.target.files?.[0];
                  if (next) setFile(next);
                }}
              />
            </div>
            {file && (
              <div className="flex items-center gap-2 rounded-[8px] border border-border px-3 py-2 text-ui">
                <FileSpreadsheet className="size-[var(--icon-sm)] text-muted-foreground" />
                <span className="truncate">{file.name}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {(["total", "valid", "warning", "invalid", "duplicate"] as const).map((key) => (
                <div key={key} className="rounded-[8px] border border-border bg-muted/20 px-3 py-2">
                  <div className="text-subheading font-semibold">{draft.summary[key] ?? 0}</div>
                  <div className="text-micro text-muted-foreground">
                    {t(`tradeImport.summary.${key}`)}
                  </div>
                </div>
              ))}
            </div>

            {draft.status === "needs_review" && draft.source_kind !== "image" && (
              <div className="rounded-[10px] border border-border bg-muted/20 p-3">
                <div className="mb-3 flex items-center gap-2">
                  <AlertCircle className="size-[var(--icon-sm)] text-[var(--warning)]" />
                  <span className="text-ui font-medium">{t("tradeImport.mappingTitle")}</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  {fields.map((field) => (
                    <div key={field} className="space-y-1">
                      <Label className="text-caption">{t(`tradeImport.field.${field}`)}</Label>
                      <Select
                        value={mapping[field] ?? "__none__"}
                        onValueChange={(value) => setMapping((current) => {
                          const next = { ...current };
                          if (value === "__none__") delete next[field];
                          else next[field] = value;
                          return next;
                        })}
                      >
                        <SelectTrigger className="w-full" style={controlStyle}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__none__">{t("tradeImport.notMapped")}</SelectItem>
                          {columns.map((column) => (
                            <SelectItem key={column} value={column}>{column}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                  <div className="space-y-1">
                    <Label className="text-caption">{t("tradeImport.timezone")}</Label>
                    <Input
                      value={mapping.__timezone ?? ""}
                      onChange={(event) => setMapping((current) => ({
                        ...current,
                        __timezone: event.target.value,
                      }))}
                      style={controlStyle}
                      placeholder="Asia/Shanghai"
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="max-h-[340px] overflow-auto rounded-[10px] border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>{t("tradeImport.rowStatus")}</TableHead>
                    <TableHead>{t("journal.symbol")}</TableHead>
                    <TableHead>{t("journal.direction")}</TableHead>
                    <TableHead>{t("tradeImport.rowIssues")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {draft.rows.slice(0, 100).map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.row_number}</TableCell>
                      <TableCell>{t(`tradeImport.status.${row.status}`)}</TableCell>
                      <TableCell>{String(row.normalized_data.symbol ?? "—")}</TableCell>
                      <TableCell>{String(
                        row.normalized_data.direction ?? row.normalized_data.side ?? "—",
                      )}</TableCell>
                      <TableCell className="max-w-[360px] text-caption text-muted-foreground">
                        {row.issues.length
                          ? row.issues.map((issue) => t(`tradeImport.issue.${issue.code}`, {
                            defaultValue: issue.code,
                          })).join("；")
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" size="sm" style={controlStyle} onClick={close} disabled={loading}>
            {t("common.cancel")}
          </Button>
          {!draft ? (
            <Button size="sm" style={controlStyle} disabled={!file || loading} onClick={() => void prepare()}>
              {t("tradeImport.prepare")}
            </Button>
          ) : draft.status === "needs_review" ? (
            <Button size="sm" style={controlStyle} disabled={loading} onClick={() => void recompute()}>
              {t("tradeImport.recompute")}
            </Button>
          ) : (
            <Button size="sm" style={controlStyle} disabled={draft.status !== "ready" || loading} onClick={() => void commit()}>
              {t("tradeImport.commit")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
