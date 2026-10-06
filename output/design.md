# Campus Customs — Storefront Design

The goal is a premium, Apple-style storefront: big type, bold color, clean product shots, and smooth motion. It should make shoppers stay, browse, and buy.

## What changed and why it sells

| Area | What changed | Why it helps customers stay and buy |
|---|---|---|
| **Fonts** | **Bricolage Grotesque** for headlines, **Inter** for text, **Instrument Serif** *italic* for accent words ("Made to *wear.*") | A distinctive look feels like a real brand, not a template. Shoppers trust it more. |
| **Color** | Yale navy anchor, deep-night hero sections, an electric sky-blue gradient for highlights, and a warm coral spark | High contrast pulls the eye to products and buttons. The dark and light sections give the page rhythm. |
| **Hierarchy** | Huge headlines, short lines, one main button per section (white or navy pill) plus a "Learn more ›" text link | Shoppers grasp each section in a second and always know the next click. |
| **Product presentation** | Photo backgrounds removed automatically (100 of 102 products), so every item sits on the same soft stage with a shadow | The catalogue looks consistent and premium. The clothing, not the old photo backgrounds, gets the attention. |
| **Product cards** | Gentle 3D tilt and light sheen on hover, real color swatches, "Almost gone" badges | Cards feel tactile and invite clicks. Low-stock badges create urgency. |
| **Card → product page** | The card's photo glides into place as the big product photo (view transition) | It feels like an app, and shoppers don't lose their place. |
| **Product page** | Large stage with hover-to-zoom, color chips, size pills with low-stock dots, a trust row (free shipping over $75, secure checkout, ask the assistant), and collapsible details | Shoppers see fabric and print detail up close, the buy button stays prominent, and doubts are answered on the spot. |
| **Motion** | Page fade-in, content that rises into view on scroll, count-up numbers, floating hero products, glow that follows the pointer | Motion rewards scrolling, so people explore further down the page. |
| **Header** | Frosted-glass bar that firms up on scroll, rotating announcements (free shipping, compare, assistant) | Search, cart, and navigation stay one tap away. The offers get seen without banner clutter. |

## Home page, top to bottom

1. **Hero:** "Campus pride. *Made to wear.*" with three floating products and a price tag that links to the featured hoodie. It makes the first impression and gives a one-click path to a product.
2. **Word ribbon:** a scrolling band of categories that shows the range at a glance.
3. **Feature tiles:** Hoodies, Game Day, Quarter-Zips, Everyday tees, each with real "From $" pricing and a Shop button. These are big, simple doors into each category.
4. **"A day on campus" story:** the section pins in place while 8 AM lecture → game day → late-night library swap products as you scroll. It tells a story and sells a lifestyle, not just items.
5. **Campus favorites carousel:** a swipeable row of well-stocked items, so shoppers browse without leaving the page.
6. **Stats:** 102 styles, 6 categories, XS–XXL, from $32, free shipping at $75, all live numbers. These are fast proof points that answer price and size questions.
7. **Category grid:** bento-style tiles with product cutouts and live counts and prices, letting shoppers jump straight to what they want.
8. **Features row:** Ask the assistant (opens chat), Compare, Saved cart. It surfaces the tools that help shoppers decide.
9. **Closing call to action:** "Your new favorite *is in here.*", a last push into the full catalogue.

**Products** gets a big title and a sticky glass filter bar with category counts. **About** gets a dark editorial hero with floating products and numbered values. **Log in and Create account** get a frosted card on a soft color glow. The **footer** ends with a giant outlined wordmark.

## Guardrails

- **Still fast:** fonts are self-hosted (about 130 KB, and text shows immediately). Cutouts are compressed WebP and lazy-loaded. Motion uses GPU-friendly transforms.
- **Accessible:** shoppers who set "reduce motion" get a calm, static site. Focus rings are visible, and the layout works on phones.
- **Honest:** prices, stock, sizes, and colors on every new section come from the database.
- **Nothing lost:** cart, compare, breadcrumbs, search, chat assistant, checkout, and the admin dashboard all still work, and were retested after the redesign.
