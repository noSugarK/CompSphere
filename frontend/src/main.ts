import { createApp } from 'vue';
import { createPinia } from 'pinia';
import 'element-plus/theme-chalk/base.css';
import 'element-plus/es/components/message/style/css';
import 'element-plus/es/components/message-box/style/css';
import 'element-plus/theme-chalk/dark/css-vars.css';
import './styles/tokens.css';
import './styles/app.css';
import App from './App.vue';
import { router } from './router';
import { i18n } from './locales';

createApp(App).use(createPinia()).use(i18n).use(router).mount('#app');
