import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const createSession = async (userName, position) => {
    const response = await axios.post(`${API_BASE_URL}/sessions`, {
        user_name: userName,
        position: position
    });
    return response.data;
};

export const getQuestions = async (sessionId) => {
    const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}/questions`);
    return response.data;
};

export const submitAnswer = async (questionId, answerText) => {
    const response = await axios.post(`${API_BASE_URL}/answers`, {
        question_id: questionId,
        answer_text: answerText
    });
    return response.data;
};

export const getResults = async (sessionId) => {
    const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}/results`);
    return response.data;
};
