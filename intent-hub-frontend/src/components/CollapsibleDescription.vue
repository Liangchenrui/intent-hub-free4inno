<template>
  <div class="description">
    <div ref="content" class="description-text" :class="{ collapsed: !expanded }">{{ text }}</div>
    <el-button v-if="overflowing || expanded" link type="primary" class="toggle"
      :aria-expanded="expanded" @click.stop="expanded = !expanded">
      {{ locale.startsWith('zh') ? (expanded ? '收起' : '展开') : (expanded ? 'Show less' : 'Show more') }}
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps<{ text: string }>();
const { locale } = useI18n();
const content = ref<HTMLElement>();
const expanded = ref(false);
const overflowing = ref(false);
let observer: ResizeObserver | undefined;
const measure = () => {
  if (content.value && !expanded.value) {
    overflowing.value = content.value.scrollHeight > content.value.clientHeight + 1;
  }
};
watch(() => props.text, () => { expanded.value = false; }, { flush: 'pre' });
watch([() => props.text, expanded], measure, { flush: 'post' });
onMounted(() => {
  observer = new ResizeObserver(measure);
  if (content.value) observer.observe(content.value);
  measure();
});
onBeforeUnmount(() => observer?.disconnect());
</script>

<style scoped>
.description { min-width: 0; font-size: 12px; color: #909399; line-height: 1.4; }
.description-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.collapsed { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.toggle { margin-top: 2px; font-size: 12px; }
</style>
