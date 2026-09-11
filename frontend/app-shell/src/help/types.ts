export interface HelpTopic {
  id: string;
  title: string;
  route?: string;
  content: string;
}

export interface ApplicationHelpConfig {
  topics: HelpTopic[];
  buttonLabel?: string;
  buttonAriaLabel?: string;
  drawerTitle?: string;
  emptyDescription?: string;
  contextualMessage?: string;
  routeDescriptionPrefix?: string;
  generalDescription?: string;
  drawerWidth?: number;
  tableOfContentsTitle?: string;
  /**
   * Карта URL для изображений, на которые ссылаются документы справки.
   * Ключ — имя файла или путь, указанный в markdown.
   */
  assetUrls?: Record<string, string>;
}
