/** Names for where users come from: first-touch sources (src/attribution.ts) and survey answers. */

/** First-touch source keys from the backend's classify() → display names. */
export const SOURCE_NAMES: Record<string, string> = {
  youtube: 'YouTube', google: 'Google', bing: 'Bing', chatgpt: 'ChatGPT', perplexity: 'Perplexity',
  claude: 'Claude', copilot: 'Copilot', duckduckgo: 'DuckDuckGo', baidu: '百度 Baidu',
  xiaohongshu: '小红书', facebook: 'Facebook', instagram: 'Instagram', reddit: 'Reddit', wechat: '微信 WeChat',
}

/** Post-purchase "how did you hear about us?" choices; values match HeardFromAnswer in the backend. */
export const HEARD_FROM = [
  { value: 'youtube', zh: 'YouTube 视频', en: 'YouTube video', zhHant: 'YouTube 影片' },
  { value: 'xiaohongshu', zh: '小红书', en: 'Xiaohongshu (RED)', zhHant: '小紅書' },
  { value: 'wechat', zh: '微信群 / 朋友圈', en: 'WeChat', zhHant: '微信群 / 朋友圈' },
  { value: 'google', zh: 'Google 搜索', en: 'Google search', zhHant: 'Google 搜尋' },
  { value: 'friend', zh: '朋友推荐', en: 'A friend told me', zhHant: '朋友推薦' },
  { value: 'instructor', zh: '驾校 / 教练', en: 'Driving school / instructor', zhHant: '駕校 / 教練' },
  { value: 'other', zh: '其他', en: 'Other', zhHant: '其他' },
] as const

export type HeardFrom = (typeof HEARD_FROM)[number]['value']
