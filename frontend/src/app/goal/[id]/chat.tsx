import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { revisionArrived, useChat, useDecideRevision, useGoal, useMarkRead, useSendMessage } from '@/api/hooks';
import type { ChatMessage } from '@/api/types';
import { Bubble } from '@/components/Bubble';
import { useI18n } from '@/i18n/I18nContext';
import { textDir } from '@/lib/text';
import { AppText, Button, Icon, type IconName, Row } from '@/ui';
import { fonts, MAX_WIDTH, radius, space, useColors } from '@/ui/theme';

function MessageItem({ msg, goalId }: { msg: ChatMessage; goalId: number }) {
  const { t } = useI18n();
  const c = useColors();
  const decide = useDecideRevision(goalId);
  const labels: Partial<Record<ChatMessage['kind'], [IconName, string, string]>> = {
    checkin: ['bell', t('checkinLabel'), c.accent],
    revision_applied: ['refresh-cw', t('planUpdatedLabel'), c.success],
    revision_proposal: ['edit-3', t('proposalLabel'), c.warning],
    safety: ['heart', t('supportLabel'), c.danger],
  };
  const label = labels[msg.kind];
  const tint = msg.kind === 'safety' ? c.dangerSoft : msg.kind === 'revision_proposal' ? c.warningSoft : undefined;
  const decision = msg.meta.decision;

  return (
    <View style={{ marginTop: label ? space.sm : 0 }}>
      {label ? (
        <Row style={{ gap: 4, marginBottom: 3 }}>
          <Icon name={label[0]} size={11} color={label[2]} />
          <AppText size={11} weight="500" style={{ color: label[2] }}>{label[1]}</AppText>
        </Row>
      ) : null}
      <Bubble text={msg.content} mine={msg.role === 'user'} tint={tint}>
        {msg.kind === 'revision_proposal' && msg.meta.revision_id ? (
          decision ? (
            <AppText muted size={12} style={{ marginTop: 4 }}>
              {decision === 'approved' ? t('approved') : t('rejected')}
            </AppText>
          ) : (
            <Row style={{ marginTop: space.sm }}>
              <Button title={t('approve')} icon="check" small loading={decide.isPending}
                onPress={() => decide.mutate({ revisionId: msg.meta.revision_id!, approve: true })} />
              <Button title={t('reject')} small variant="ghost" disabled={decide.isPending}
                onPress={() => decide.mutate({ revisionId: msg.meta.revision_id!, approve: false })} />
            </Row>
          )
        ) : null}
      </Bubble>
    </View>
  );
}

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const goalId = Number(id);
  const { t, isRTL } = useI18n();
  const c = useColors();
  const goal = useGoal(goalId);
  // Id of the reply after which a plan revision is expected (it is prepared in the background).
  const [waitAfterId, setWaitAfterId] = useState<number | null>(null);
  const chat = useChat(goalId, waitAfterId);
  const send = useSendMessage(goalId);
  const markRead = useMarkRead();
  const [text, setText] = useState('');
  const list = useRef<FlatList<ChatMessage>>(null);
  const messages = useMemo(() => chat.data ?? [], [chat.data]);
  const waitingForRevision = waitAfterId !== null && !revisionArrived(messages, waitAfterId);
  const lastId = messages.at(-1)?.id;

  useEffect(() => {
    markRead.mutate({ goalId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goalId, lastId]);

  // Give up waiting for a revision after 30 s.
  useEffect(() => {
    if (waitAfterId === null) return;
    const timer = setTimeout(() => setWaitAfterId(null), 30_000);
    return () => clearTimeout(timer);
  }, [waitAfterId]);

  const submit = () => {
    const content = text.trim();
    if (!content || send.isPending) return;
    setText('');
    send.mutate(content, { onSuccess: (out) => out.revision_in_progress && setWaitAfterId(out.reply.id) });
  };

  const status = send.isPending ? t('coachTyping') : waitingForRevision ? t('preparingUpdate') : null;

  return (
    <SafeAreaView edges={['bottom', 'left', 'right']} style={{ flex: 1, backgroundColor: c.bg }}>
      <Stack.Screen options={{ title: goal.data?.title ?? t('chat') }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        <FlatList
          ref={list}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          renderItem={({ item }) => <MessageItem msg={item} goalId={goalId} />}
          contentContainerStyle={{ paddingHorizontal: space.lg, paddingVertical: space.md, width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center' }}
          onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
          ListFooterComponent={status ? <AppText muted size={12} style={{ marginTop: 4 }}>{status}</AppText> : undefined}
        />
        {send.error ? <AppText size={13} style={{ color: c.danger, paddingHorizontal: space.lg }}>{send.error.message}</AppText> : null}
        <View style={{ backgroundColor: c.bg, paddingHorizontal: space.md, paddingVertical: space.sm }}>
          <Row style={{ width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', alignItems: 'flex-end', backgroundColor: c.surface, borderRadius: 22, borderWidth: 1, borderColor: c.border, padding: 4 }}>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder={t('chatPh')}
              placeholderTextColor={c.faint}
              multiline
              onKeyPress={(e) => {
                // Enter sends on web; Shift+Enter makes a new line.
                const ne = e.nativeEvent as unknown as { key: string; shiftKey?: boolean };
                if (Platform.OS === 'web' && ne.key === 'Enter' && !ne.shiftKey) {
                  (e as unknown as { preventDefault: () => void }).preventDefault();
                  submit();
                }
              }}
              style={[
                { flex: 1, maxHeight: 120, paddingHorizontal: 12, paddingVertical: 8, color: c.text, fontSize: 14, fontFamily: fonts['400'] },
                textDir(text || t('chatPh')),
              ]}
            />
            <Pressable
              onPress={submit}
              disabled={!text.trim() || send.isPending}
              accessibilityLabel={t('send')}
              style={{ width: 36, height: 36, borderRadius: radius.pill, backgroundColor: text.trim() ? c.primary : c.fill, alignItems: 'center', justifyContent: 'center', transform: [{ scaleX: isRTL ? -1 : 1 }] }}>
              <Icon name="send" size={16} color={text.trim() ? c.onPrimary : c.faint} />
            </Pressable>
          </Row>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
