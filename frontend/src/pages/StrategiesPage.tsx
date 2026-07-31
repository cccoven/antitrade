import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  animatedLineTabClassName,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import FlushPage from "@/components/FlushPage";
import TradingRulesPanel from "@/components/TradingRulesPanel";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import {
  type Strategy,
  listStrategies,
  createStrategy,
  deleteStrategy,
} from "@/api/strategies";
import StrategyCard from "./strategies/StrategyCard";
import {
  captionStyle,
  inputStyle,
  strategiesGalleryLayout,
  strategiesToolbarControlSizes,
} from "./strategies-ui-config";

const sizes = strategiesToolbarControlSizes;
const buttonStyle = { fontSize: sizes.fontSize, fontWeight: sizes.fontWeight };

export default function StrategiesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<Strategy[] | null>(null);
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState("strategies");

  useEffect(() => {
    if (!user) return;
    listStrategies().then(setItems).catch(() => setItems([]));
  }, [user]);

  const filtered = useMemo(() => {
    if (!items) return [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((s) => {
      const hay = (s.title + " " + s.body + " " + s.tags.join(" ")).toLowerCase();
      return hay.includes(q);
    });
  }, [items, query]);

  const onCreate = async () => {
    const created = await createStrategy({});
    setItems((prev) => (prev ? [created, ...prev] : [created]));
    navigate(`/strategies/${created.id}?new=1`);
  };

  const onDelete = async (id: string) => {
    await deleteStrategy(id);
    setItems((prev) => (prev ? prev.filter((s) => s.id !== id) : prev));
  };

  if (authLoading) return null;
  if (!user) return <LoginRequiredPage />;

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="gap-0">
    <FlushPage
      toolbar={
        <div className="flex items-center gap-2">
          <TabsList variant="line" className="h-7 gap-3 p-0">
            <TabsTrigger value="strategies" style={captionStyle} className={animatedLineTabClassName}>
              {t("strategies.tab.strategies")}
            </TabsTrigger>
            <TabsTrigger value="rules" style={captionStyle} className={animatedLineTabClassName}>
              {t("strategies.tab.rules")}
            </TabsTrigger>
          </TabsList>
          {activeTab === "strategies" ? (
            <TooltipIconButton
              label={t("strategies.new")}
              size={sizes.iconAction}
              style={buttonStyle}
              onClick={onCreate}
            >
              <Plus />
            </TooltipIconButton>
          ) : null}
        </div>
      }
      toolbarAside={
        activeTab === "strategies" ? <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("strategies.searchPlaceholder")}
          style={inputStyle}
          className="w-64"
        /> : null
      }
    >
      <TabsContent value="strategies" className="mt-0">
      {items === null ? (
        <div className="text-caption text-muted-foreground">{t("common.loading")}</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center py-16">
          <div className="text-caption text-muted-foreground">{t("strategies.empty")}</div>
        </div>
      ) : (
        <div className={strategiesGalleryLayout.gridClassName}>
          {filtered.map((s) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              onClick={() => navigate(`/strategies/${s.id}`)}
              onDelete={() => onDelete(s.id)}
            />
          ))}
        </div>
      )}
      </TabsContent>
      <TabsContent value="rules" className="mt-0">
        <TradingRulesPanel />
      </TabsContent>
    </FlushPage>
    </Tabs>
  );
}
