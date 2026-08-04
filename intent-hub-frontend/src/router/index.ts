import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import AgentList from '../views/AgentList.vue';
import AgentTest from '../views/AgentTest.vue';
import Diagnostics from '../views/Diagnostics.vue';
import Settings from '../views/Settings.vue';

const routes = [
  { path: '/login', name: 'Login', component: Login, meta: { public: true } },
  { path: '/', name: 'AgentList', component: AgentList },
  { path: '/test', name: 'AgentTest', component: AgentTest },
  { path: '/diagnostics', name: 'Diagnostics', component: Diagnostics },
  { path: '/settings', name: 'Settings', component: Settings },
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach((to, _from, next) => {
  if (!to.meta.public && !localStorage.getItem('api_key')) {
    next({ name: 'Login' });
    return;
  }
  next();
});

export default router;
