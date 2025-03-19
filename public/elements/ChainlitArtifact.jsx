import { Markdown } from "@/components/markdown";
import { Renderer } from "@/components/renderer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Artifact() {
  const sourceCodeMarkdown = "```jsx\n" + props.sourceCode + "```";

  return (
    <Tabs defaultValue="preview">
      <div className="flex flex-col gap-4">
        <div className="flex w-full flex-wrap justify-between">
          <div className="text-lg font-bold">{props.name}</div>
          <TabsList className="grid w-fit grid-cols-2">
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="code">Code</TabsTrigger>
          </TabsList>
        </div>
        <div>
          <TabsContent value="preview">
            <Renderer sourceCode={props.sourceCode} props={props.props} />
          </TabsContent>
          <TabsContent value="code">
            <Markdown>{sourceCodeMarkdown}</Markdown>
          </TabsContent>
        </div>
      </div>
    </Tabs>
  );
}
