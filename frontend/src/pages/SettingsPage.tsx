import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { KeywordsTab } from '@/components/settings/KeywordsTab'
import { ScoringTab } from '@/components/settings/ScoringTab'
import { NotificationsTab } from '@/components/settings/NotificationsTab'
import { AgentRunsTab } from '@/components/settings/AgentRunsTab'
import { ScheduleTab } from '@/components/settings/ScheduleTab'

export function SettingsPage() {
  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Separator className="my-4" />
      {/* Watchlists tab removed in quick-260420-sn9 — Twitter agent purged (no consumer). */}
      <Tabs defaultValue="keywords">
        <TabsList>
          <TabsTrigger value="keywords">Keywords</TabsTrigger>
          <TabsTrigger value="scoring">Scoring</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="agent-runs">Agent Runs</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
        </TabsList>
        <TabsContent value="keywords">
          <KeywordsTab />
        </TabsContent>
        <TabsContent value="scoring">
          <ScoringTab />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>
        <TabsContent value="agent-runs">
          <AgentRunsTab />
        </TabsContent>
        <TabsContent value="schedule">
          <ScheduleTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
