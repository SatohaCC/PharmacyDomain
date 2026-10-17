import type { Preview } from "@storybook/react-vite";
import { Canvas, Page } from "../src/shared/ui/layout/elements";
import { NavigationProvider } from "../src/shared/ui/navigation/link";
import "../src/style.css";
const preview: Preview = {
  decorators: [
    (Story, context) => (
      <NavigationProvider navigate={() => {}}>
        <Canvas>
          {context.parameters.standalone ? (
            <Story />
          ) : (
            <Page>
              <Story />
            </Page>
          )}
        </Canvas>
      </NavigationProvider>
    ),
  ],
  parameters: { layout: "fullscreen", a11y: { test: "error" } },
};
export default preview;
