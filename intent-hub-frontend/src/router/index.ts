import { createRouter, createWebHistory } from 'vue-router';
import AgentList from '../views/AgentList.vue';
import AgentTest from '../views/AgentTest.vue';
import Settings from '../views/Settings.vue';
import Diagnostics from '../views/Diagnostics.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: AgentList },
    { path: '/test', component: AgentTest },
    { path: '/diagnostics', component: Diagnostics },
    { path: '/settings', component: Settings },
  ],
});

export default router;
