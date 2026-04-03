import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { WatchlistTab } from '@/components/settings/WatchlistTab'
import { KeywordsTab } from '@/components/settings/KeywordsTab'

export function SettingsPage() {
  return (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Separator className="my-4" />
      <Tabs defaultValue="watchlists">
        <TabsList>
          <TabsTrigger value="watchlists">Watchlists</TabsTrigger>
          <TabsTrigger value="keywords">Keywords</TabsTrigger>
          <TabsTrigger value="scoring">Scoring</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="agent-runs">Agent Runs</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
        </TabsList>
        <TabsContent value="watchlists">
          <WatchlistTab />
        </TabsContent>
        <TabsContent value="keywords">
          <KeywordsTab />
        </TabsContent>
        <TabsContent value="scoring">
          <p className="text-sm text-muted-foreground p-4">Coming soon</p>
        </TabsContent>
        <TabsContent value="notifications">
          <p className="text-sm text-muted-foreground p-4">Coming soon</p>
        </TabsContent>
        <TabsContent value="agent-runs">
          <p className="text-sm text-muted-foreground p-4">Coming soon</p>
        </TabsContent>
        <TabsContent value="schedule">
          <p className="text-sm text-muted-foreground p-4">Coming soon</p>
        </TabsContent>
      </Tabs>
    </div>
  )
}
